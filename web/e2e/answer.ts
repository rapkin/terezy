import { expect, type Page } from "@playwright/test";
import { AS_OF } from "./offline";

/** The answer the API serves for the one declared question, read by the test rather than assumed. */
export type ServedAnswer = {
  readonly sections: {
    readonly nonDominated: readonly string[];
    readonly ranked: number;
    readonly noCandidate: number;
  }[];
};

/**
 * The answer over the API, asked for by the page's own origin.
 *
 * Read in the browser and not pinned in the test: `data/` moves, and a figure copied out of it
 * would make this a test of the registry (021 FR-047). What is asserted is the *relation* — the
 * screen's members are the API's members.
 */
export async function servedAnswer(page: Page): Promise<ServedAnswer> {
  return await page.evaluate(async (asOf: string) => {
    const declared: { ids: string[] } = await (await fetch(`/api/questions?as_of=${asOf}`)).json();
    const [questionId] = declared.ids;
    const body: {
      result: {
        answer: {
          sections: {
            dominance: { non_dominated?: { instrument_id: string }[] };
            outcome: {
              comparison: { ranked?: unknown[] };
              enumerated: { no_candidate: unknown[] };
            };
          }[];
        };
      };
    } = await (
      await fetch(`/api/questions/${String(questionId)}/answer?as_of=${asOf}`)
    ).json();
    return {
      sections: body.result.answer.sections.map((section) => ({
        nonDominated: (section.dominance.non_dominated ?? []).map((held) => held.instrument_id),
        ranked: (section.outcome.comparison.ranked ?? []).length,
        noCandidate: section.outcome.enumerated.no_candidate.length,
      })),
    };
  }, AS_OF);
}

/** Wait for the answer itself, not merely for the page: the fetch is megabytes (OB-10). */
export async function openTheAnswer(page: Page): Promise<void> {
  await page.goto(`/?as_of=${AS_OF}`);
  await expect(page.locator("[data-answer]")).toBeVisible({ timeout: 120_000 });
}
