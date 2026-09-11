import { expect, type Page } from "@playwright/test";
import { AS_OF } from "./offline";

/** The answer the API serves for the one declared question, read by the test rather than assumed. */
export type ServedAnswer = {
  readonly sections: {
    readonly nonDominated: readonly string[];
    readonly evaluated: number;
    readonly beatsBenchmark: readonly string[];
    readonly dominated: number;
    readonly notPlaced: number;
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
            dominance: {
              non_dominated?: { instrument_id: string }[];
              evaluated_count?: number;
              dominated?: unknown[];
              not_placed?: unknown[];
            };
            outcome: {
              comparison: {
                ranked?: { key: { instrument_id: string } }[];
                beats_benchmark?: number[];
              };
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
        evaluated: section.dominance.evaluated_count ?? -1,
        // Resolved here rather than counted: `beats_benchmark` is a list of indices into
        // `ranked`, and a count is green whatever member each index lands on.
        beatsBenchmark: (section.outcome.comparison.beats_benchmark ?? []).map(
          (at) => (section.outcome.comparison.ranked ?? [])[at]?.key.instrument_id ?? "?",
        ),
        dominated: (section.dominance.dominated ?? []).length,
        notPlaced: (section.dominance.not_placed ?? []).length,
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
