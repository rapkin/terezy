import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { REPO } from "../tools/openapi.mjs";
import { AS_OF, offline } from "./offline";

/**
 * US1's independent test: a mark survives from a TOML file to a pixel.
 *
 * The citation, `retrieved_on` and `verified_on` read off the card are looked for in the file the
 * card itself names -- which is the one thing a screenshot cannot fake, and the reason the
 * declaring path is a requirement rather than a nicety (FR-018).
 */
test("a citation on the card is the citation in the file the card names", async ({ page }) => {
  await offline(page);
  await page.goto(`/data/official-rates/ua_nbu_usd?as_of=${AS_OF}`);

  const declared = await page.locator("[data-declared-in]").first().getAttribute("data-declared-in");
  expect(declared).not.toBeNull();
  const onDisk = readFileSync(join(REPO, "data", declared ?? ""), "utf8");

  const source = page.locator("[data-provenance] li").first();
  const citation = (await source.locator("[data-citation]").textContent()) ?? "";
  expect(citation.length).toBeGreaterThan(20);
  expect(onDisk).toContain(citation);

  const rendered = (await source.textContent()) ?? "";
  const retrieved = /retrieved_on (\d{4}-\d{2}-\d{2})/.exec(rendered);
  expect(retrieved).not.toBeNull();
  expect(onDisk).toContain(retrieved?.[1] ?? "");
  expect(rendered).toContain("verified_on");
});

test("an exempt directory renders the exemption with its reason, not an empty citation block", async ({
  page,
}) => {
  await offline(page);
  await page.goto(`/data/goals/flat_deposit?as_of=${AS_OF}`);
  const exemption = page.locator("[data-citations='exempt']").first();
  await expect(exemption).toBeVisible();
  const reason = (await exemption.textContent()) ?? "";
  expect(reason.replace("citations exempt for goals — ", "").trim().length).toBeGreaterThan(10);
});
