import { expect, test } from "@playwright/test";
import { quantity } from "@/design/format";
import { AS_OF, offline } from "./offline";
import { openTheAnswer } from "./answer";

/**
 * SC-003 and SC-004: the belief is stated once, and no unrounded float reaches the document.
 *
 * *Unrounded* is measured three ways, because the page renders three kinds of text. Every figure
 * slot is checked outright; the rest of the visible page is checked with the served text
 * excluded, since a citation the API wrote — `the gap is 0.000% to 0.637%` — is a quotation and
 * not a figure this client formatted. Eliding it would be 021's *Edge Cases* prohibition.
 *
 * A quantity is the third, and it is exempt from the two-decimal rule rather than from the scan:
 * money is stated to the kopeck and a holding is subdivided down to the satoshi, so a lot of a
 * fraction of a coin is a correctly rounded figure the two-decimal rule called a raw float.
 */
const UNROUNDED = /\d\.\d{3,}|\d[eE][+-]?\d/;

/** FR-026's quantity precision: eight decimals, and never an exponent. */
const UNROUNDED_QUANTITY = /\d\.\d{9,}|\d[eE][+-]?\d/;

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

  const scanned = await page.evaluate((): { composed: string; quantities: string[] } => {
    const parts: string[] = [];
    const quantities: string[] = [];
    const main = document.querySelector("main");
    if (main === null) return { composed: "", quantities };
    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node !== null) {
      const parent = node.parentElement;
      // Text the API wrote is a quotation; text this client composed is a figure.
      if (parent !== null && parent.closest("[data-served-text]") === null) {
        const text = node.textContent ?? "";
        if (parent.closest("[data-quantity]") === null) parts.push(text);
        else quantities.push(text);
      }
      node = walker.nextNode();
    }
    return { composed: parts.join(" "), quantities };
  });
  expect(scanned.composed.length).toBeGreaterThan(500);
  const found = scanned.composed.match(new RegExp(UNROUNDED.source, "g"));
  expect(found, "the page composed these").toBeNull();
  // Not vacuous anywhere: the data root the API is started over declares a holding (FR-045).
  expect(scanned.quantities.length, "a holding is on the screen to scan").toBeGreaterThan(0);
  expect(scanned.quantities.filter((held) => UNROUNDED_QUANTITY.test(held))).toEqual([]);
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
    const body: {
      result: {
        answer: {
          held: { instrument_id: string; quantity: number; lots: { quantity: number }[] }[];
        };
      };
    } = await (
      await fetch(`/api/questions/${String(declared.ids[0])}/answer?as_of=${asOf}`)
    ).json();
    return body.result.answer.held;
  }, AS_OF);
  // The count is the count of POSITIONS. A position's lots are inside it and are not members of
  // this population; the empty case is a named state and is held by the unit suite.
  expect(stated).toBe(served.length);
  expect(served.length, "the data root the API was started over declares a holding").toBeGreaterThan(
    0,
  );

  await held.locator("[data-disclosure='what the owner already holds'] > summary").click();
  for (const position of served) {
    const drawn = held.locator(`[data-held='${position.instrument_id}']`);
    await expect(drawn).toHaveCount(1);
    // One disclosure per position, whatever its lots number: a second lot must not add a second.
    await expect(drawn.locator("details")).toHaveCount(1);
    await drawn.locator("details > summary").click();
    await expect(drawn.locator("[data-lot]")).toHaveCount(position.lots.length);
    // Every quantity is the formatting module's, never the number as JavaScript prints it.
    expect(await drawn.locator("[data-quantity]").allTextContents()).toEqual([
      quantity(position.quantity),
      ...position.lots.map((lot) => quantity(lot.quantity)),
    ]);
    // A valuation the registry could not strike is a refusal with its reason, never a blank.
    const worth = drawn.locator("[data-figure='marked'], [data-figure='refused']");
    expect(await worth.count()).toBeGreaterThan(0);
    expect(((await drawn.textContent()) ?? "").trim()).not.toBe("");
  }
});
