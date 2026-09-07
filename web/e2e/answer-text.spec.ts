import { expect, test } from "@playwright/test";
import { AS_OF, offline } from "./offline";
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

test("every subject is a state, declared or not, and none of them is blank", async ({ page }) => {
  test.setTimeout(300_000);
  await offline(page);
  await openTheAnswer(page);

  // 023 and 025 declared the last two, so the shipped answer reports no undeclared subject at
  // all — the assertion is over whichever the API sends rather than over a count measured once.
  const subjects = page.locator("[data-subjects] li");
  const many = await subjects.count();
  expect(many).toBeGreaterThan(0);
  for (let at = 0; at < many; at += 1) {
    expect(((await subjects.nth(at).textContent()) ?? "").trim()).not.toBe("");
  }
  for (const text of await page.locator("[data-undeclared-subject]").allTextContents()) {
    expect(text).toContain("a declaration");
  }
});

test("what the owner already holds is on the screen, valued or refused", async ({ page }) => {
  test.setTimeout(300_000);
  await offline(page);
  await openTheAnswer(page);

  const held = page.locator("[data-population='what the owner already holds']");
  const stated = Number((await held.getAttribute("data-count")) ?? "0");
  const served = await page.evaluate(async (asOf: string) => {
    const declared: { ids: string[] } = await (await fetch(`/api/questions?as_of=${asOf}`)).json();
    const body: { result: { answer: { held: { instrument_id: string }[] } } } = await (
      await fetch(`/api/questions/${String(declared.ids[0])}/answer?as_of=${asOf}`)
    ).json();
    return body.result.answer.held.map((one) => one.instrument_id);
  }, AS_OF);
  expect(stated).toBe(served.length);
  if (served.length === 0) return;

  await held.locator("summary").click();
  for (const id of served) {
    const position = held.locator(`[data-held='${id}']`);
    await expect(position).toHaveCount(1);
    // A valuation the registry could not strike is a refusal with its reason, never a blank.
    const worth = position.locator("[data-figure='marked'], [data-figure='refused']");
    expect(await worth.count()).toBeGreaterThan(0);
    expect(((await position.textContent()) ?? "").trim()).not.toBe("");
  }
});
