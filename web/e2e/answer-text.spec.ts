import { expect, test } from "@playwright/test";
import { offline } from "./offline";
import { openTheAnswer } from "./answer";

/**
 * SC-003 and SC-004: the belief is stated once, and no unrounded float reaches the document.
 *
 * *Unrounded* is measured two ways, because the page also renders the engine's own prose. Every
 * figure slot is checked outright; the rest of the visible page is checked with the served text
 * excluded, since a citation the API wrote — `the gap is 0.000% to 0.637%` — is a quotation and
 * not a figure this client formatted. Eliding it would be 021's *Edge Cases* prohibition.
 */
const UNROUNDED = /\d\.\d{3,}|\d[eE][+-]?\d/;

test("the early-exit belief is stated once, and each card leaning on it carries a mark", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await offline(page);
  await openTheAnswer(page);

  const lines = page.locator("[data-belief]");
  const many = await lines.count();
  expect(many).toBeGreaterThan(0);
  const ids = await lines.evaluateAll((held) =>
    held.map((one) => one.getAttribute("data-belief") ?? ""),
  );
  expect(new Set(ids).size, "a belief is stated once per distinct id").toBe(ids.length);

  const marks = await page
    .locator("[data-belief-mark]")
    .evaluateAll((held) => held.map((one) => one.getAttribute("data-belief-mark") ?? ""));
  expect(marks.length).toBeGreaterThan(0);
  for (const mark of new Set(marks)) expect(ids).toContain(mark);

  // The mark is a mark and not a copy: the statement itself is in the line, once. Read as text
  // content rather than as rendered text — FR-025 puts it behind a disclosure, so it is in the
  // document and off the screen until a reader asks for it.
  const rationale = (await page.locator("[data-served-text='belief']").first().textContent()) ?? "";
  expect(rationale.length).toBeGreaterThan(80);
  const cards = await page.locator("[data-candidate]").allTextContents();
  expect(cards.length).toBeGreaterThan(0);
  for (const card of cards) expect(card).not.toContain(rationale.slice(0, 60));
});

test("no unrounded float reaches the document", async ({ page }) => {
  test.setTimeout(300_000);
  await offline(page);
  await openTheAnswer(page);

  const slots = await page.locator("[data-figure]").allTextContents();
  expect(slots.length).toBeGreaterThan(0);
  expect(slots.filter((held) => UNROUNDED.test(held))).toEqual([]);

  const composed = await page.evaluate(() => {
    const main = document.querySelector("main");
    if (main === null) return "";
    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
    const parts: string[] = [];
    let node = walker.nextNode();
    while (node !== null) {
      const parent = node.parentElement;
      // Text the API wrote is a quotation; text this client composed is a figure.
      if (parent !== null && parent.closest("[data-served-text]") === null) {
        parts.push(node.textContent ?? "");
      }
      node = walker.nextNode();
    }
    return parts.join(" ");
  });
  expect(composed.length).toBeGreaterThan(500);
  const found = composed.match(new RegExp(UNROUNDED.source, "g"));
  expect(found, "the page composed these").toBeNull();
});

test("every undeclared subject carries its remedy and the feature that supplies it", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await offline(page);
  await openTheAnswer(page);

  const subjects = page.locator("[data-undeclared-subject]");
  const many = await subjects.count();
  expect(many).toBeGreaterThan(0);
  for (let at = 0; at < many; at += 1) {
    const subject = subjects.nth(at);
    await expect(subject).toContainText("a declaration");
    // FR-021: a third undeclared subject with no entry renders `unrecorded`, which fails here
    // rather than rendering blank.
    const feature = await subject.locator("[data-remedy-feature]").getAttribute("data-remedy-feature");
    expect(feature).not.toBe("unrecorded");
  }
});
